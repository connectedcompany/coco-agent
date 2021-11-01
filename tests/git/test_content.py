from coco_agent.services.git import content


def test_lines_python():
    res = content.get_lines(
        "abc/myfile.py",
        """
import os

# example method
def aa():

    print("hello")

""",
        encoding="utf-8",
    )

    assert res == dict(language="Python", code=3, documentation=1, empty=2, string=0)


def test_lines_java():
    res = content.get_lines(
        "abc/myfile.java",
        """
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.URL;

/*
 Here is a block comment

 * It can span multiple lines
 * It can have all kinds of things inside it
 *...

*/
public class Main {
    // here's the main method
    public static void main(String[] args) {
        try
        {
            URL my_url= new URL("http://www.viralpatel.net/blogs/");
            BufferedReader br = newBufferedReader(new InputStreamReader(my_url.openStream()));
            String strTemp =""; while(null != (strTemp = br.readLine())){
                System.out.println(strTemp);
            }
        } catch (Exception ex) {
            ex.printStackTrace();
        }
    }
}
""",
        encoding="utf-8",
    )

    assert res == dict(language="Java", code=12, documentation=9, empty=6, string=0)
